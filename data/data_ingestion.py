import os
import json
import pytz
import gspread
from datetime import datetime, timezone
from dotenv import load_dotenv

from app.services.supabase_service import store_data_in_supabase


load_dotenv()

# google sheets Configuration
GOOGLE_SERVICE_ACCOUNT_KEY_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
TARGET_SHEET_NAME = os.getenv("TARGET_SHEET_NAME", "products")
ID_COLUMN_HEADER = os.getenv("ID_COLUMN_HEADER", "Id")

# timestamp management
LAST_INGESTION_TIMESTAMP_FILE = 'data/last_ingestion_timestamp.json'
TIMEZONE = pytz.utc
FIRST_RUN_TIMESTAMP = datetime.min.replace(tzinfo=TIMEZONE)


# --- helper functions ---

def load_last_ingestion_timestamp():
    """Load the last ingestion timestamp from a JSON file."""
    if os.path.exists(LAST_INGESTION_TIMESTAMP_FILE):
        try:
            with open(LAST_INGESTION_TIMESTAMP_FILE, 'r') as f:
                data = json.load(f)
                timestamp_str = data.get("last_timestamp")
                if timestamp_str:
                    return datetime.fromisoformat(timestamp_str).replace(tzinfo=TIMEZONE)
        except Exception as e:
            print(f"Error loading last ingestion timestamp: {e}")
            pass
    print("No valid last ingestion timestamp found, using first run timestamp.")
    return FIRST_RUN_TIMESTAMP

def save_last_ingestion_timestamp(timestamp):
    """Save the last ingestion timestamp to a JSON file."""
    try:
        with open(LAST_INGESTION_TIMESTAMP_FILE, 'w') as f:
            json.dump({'last_timestamp': timestamp.isoformat()}, f)
    except IOError as e:
        print(f"Error saving last ingestion timestamp: {e}")


def get_google_sheet_data(sheet_id, sheet_name, service_account_path):
    """Fetch data from a Google Sheet and return as a list of dictionaries."""
    try:
        # authenticate using the service account key
        gc = gspread.service_account(filename=service_account_path)
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.worksheet(sheet_name)

        # get_all_values() returns a list of lists (rows), where the first list is headers
        data = worksheet.get_all_values()

        if not data:
            print("Sheet is empty.")
            return []

        # convert to a list of dictionaries with headers as keys
        headers = data[0]
        rows = data[1:]

        # create list of dictionaries, skipping rows that don't have the same number of columns as headers
        list_of_dicts = []
        for i, row in enumerate(rows):
            if len(row) == len(headers):
                list_of_dicts.append(dict(zip(headers, row)))
            else:
                # this can happen if a row has trailing empty cells that get omitted by get_all_values
                # or if the row structure is genuinely inconsistent.
                print(f"Warning: Skipping row {i+2} due to inconsistent column count. Expected {len(headers)}, got {len(row)}.")

        print(f"Successfully fetched and structured {len(list_of_dicts)} rows from sheet '{sheet_name}'.")
        return list_of_dicts

    except Exception as e:
        print(f"Error fetching Google Sheet data: {e}")
        return None

# --- main Ingestion Logic ---

def run_ingestion():
    """
    Runs the data ingestion pipeline:
    Reads all data from Google Sheet, and stores each row in Supabase/Pinecone.
    This version performs a full sync on each run.
    """
    print("Starting full data ingestion process...")
    last_timestamp = load_last_ingestion_timestamp()
    print(f"Last ingestion timestamp loaded: {last_timestamp}")

    is_first_run = (last_timestamp == FIRST_RUN_TIMESTAMP)
    if is_first_run:
        print("This is the first run. No previous ingestion timestamp found.")

    # 1. read all data from the Google Sheet using the helper function
    sheet_data = get_google_sheet_data(GOOGLE_SHEET_ID, TARGET_SHEET_NAME, GOOGLE_SERVICE_ACCOUNT_KEY_PATH)

    if not sheet_data: # handle empty sheet case or if get_google_sheet_data returned empty list
        print("Sheet data is empty after processing. Nothing to ingest.")
        save_last_ingestion_timestamp(datetime.now(tz=TIMEZONE))  # save current time as last timestamp
        print(f"Saved last ingestion timestamp as {datetime.now(tz=TIMEZONE)}.")
        return


    # double check the header is there.
    if ID_COLUMN_HEADER not in sheet_data[0].keys():
         print(f"Error: ID column header '{ID_COLUMN_HEADER}' not found in the first row's keys.")
         print(f"Available headers: {list(sheet_data[0].keys())}")
         return


    # 2. process each row dictionary
    rows_to_process = []
    processed_count = 0
    rows_skipped_no_id = 0
    rows_skipped_old_timestamp = 0
    rows_skipped_invalid_timestamp = 0

    current_ingestion_timestamp = datetime.now(tz=TIMEZONE)

    print(f"Filtering rows with timestamp >= {last_timestamp} (or all rows on first run) ....")

    print(f"Processing {len(sheet_data)} rows for storage...")

    for row_data in sheet_data:
        # ensure row_data is a dictionary (should be, based on get_google_sheet_data)
        if not isinstance(row_data, dict):
            print(f"Skipping unexpected data type in sheet_data: {type(row_data)}. Expected dict.")
            continue

        # get the unique ID for the row
        row_id = row_data.get(ID_COLUMN_HEADER)
        print(f"Processing row with ID: {row_id}")

        if not row_id:
            print(f"Skipping row due to missing or empty ID. Row data: {row_data}. Ensure the '{ID_COLUMN_HEADER}' column is populated for all rows.")
            rows_skipped_no_id += 1
            continue # skip rows without a valid ID

        timestamp_value = row_data.get('Last Updated UTC')
        row_timestamp = None

        if isinstance(timestamp_value, str) and timestamp_value.strip() != "":
            try:
                row_timestamp = datetime.strptime(timestamp_value.strip(), '%m/%d/%Y').replace(tzinfo=TIMEZONE)
            
            except ValueError as e:
                print(f"Error parsing timestamp for row ID {row_id}: {e}. Expected format is 'ddmmyy'. Skipping this row.")
                rows_skipped_invalid_timestamp += 1
                continue
        elif timestamp_value is None or (isinstance(timestamp_value, str) and timestamp_value.strip() == ""):
            row_timestamp = None
            if not is_first_run:
                print(f"Skipping row ID {row_id} due to missing or empty 'Last Updated UTC' timestamp. Ensure this column is populated for all rows.")
                rows_skipped_invalid_timestamp += 1
                continue
        else:
            print(f"Skipping row ID {row_id} due to unexpected timestamp format: {timestamp_value}. Expected a string in 'ddmmyy' format or None. Ensure this column is populated correctly.")
            rows_skipped_invalid_timestamp += 1
            continue

        # --- filtering Logic ---
        # Include row if:
        # 1. it's the first run (and has a valid ID and a timestamp that was successfully parsed or is empty)
        # or
        # 2. it's NOT the first run AND the row_timestamp is valid AND row_timestamp >= last_timestamp

        should_process = False
        if is_first_run:
            should_process = True
        elif row_timestamp is not None and row_timestamp >= last_timestamp:
            should_process = True
        else:
            rows_skipped_old_timestamp += 1

        if should_process:
            rows_to_process.append(row_data)

        print(f"Found {len(rows_to_process)} rows to process after filtering.")
        if rows_skipped_old_timestamp > 0:
            print(f"Skipped {rows_skipped_old_timestamp} rows due to old timestamps (before {last_timestamp}).")
        if rows_skipped_invalid_timestamp > 0:
            print(f"Skipped {rows_skipped_invalid_timestamp} rows due to invalid or missing timestamps.")

        if not rows_to_process:
            print("No rows to process after filtering. Exiting ingestion process.")
            save_last_ingestion_timestamp(current_ingestion_timestamp)  # Save current time as last timestamp
            print(f"Saved last ingestion timestamp as {current_ingestion_timestamp}.")
            print("Data ingestion process finished.")
            return
        
        for row_data in rows_to_process:
            if not isinstance(row_data, dict):
                print(f"Skipping unexpected data type in row_data: {type(row_data)}. Expected dict.")
                continue

            row_id = row_data.get(ID_COLUMN_HEADER)
            if not row_id:
                print(f"Missing or empty ID in row data: {row_data}. Skipping this row.")
                continue
            try:
                # store/update the original row data in Supabase
                store_data_in_supabase(row_data)
                processed_count += 1

            except Exception as e:
                print(f"Error processing row ID {row_id}: {e}")

        print(f"Finished processing. Successfully processed {processed_count} rows.")

        save_last_ingestion_timestamp(current_ingestion_timestamp)  # Save current time as last timestamp
        print(f"Saved last ingestion timestamp as {current_ingestion_timestamp}.")
        print("Data ingestion process finished.")


# --- script entry point ---

if __name__ == "__main__":
    run_ingestion()


# Things to change
#  - change some of the print statements for more accurate logging details
