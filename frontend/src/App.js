import React from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';
import Chat from './components/Chat';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Company AI Agent</h1>
      </header>
      <main>
        <Chat />
      </main>
    </div>
  );
}

export default App;