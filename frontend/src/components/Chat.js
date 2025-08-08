import React, { useState } from 'react';
import { Form, Button, Container, Row, Col, ListGroup } from 'react-bootstrap';

const Chat = () => {
  const [message, setMessage] = useState('');
  const [chatHistory, setChatHistory] = useState([]);

  const sendMessage = async () => {
    if (!message.trim()) return;

    const userMessage = { sender: 'user', content: message };
    setChatHistory([...chatHistory, userMessage]);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: message,
          name: 'gbemike',
          user_id: 'bdb91849beac0c4f', // Replace with a dynamic user ID if needed
          session_id: '83e3ed19-f66e-4352-96b2-8c04906a1b08' // Replace with a dynamic session ID if needed
         }),
      });

      const data = await response.json();
      const agentMessage = { sender: 'agent', content: data.response };
      setChatHistory(prevChatHistory => [...prevChatHistory, agentMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = { sender: 'agent', content: 'Error: Could not connect to the server.' };
      setChatHistory(prevChatHistory => [...prevChatHistory, errorMessage]);
    }

    setMessage('');
  };

  return (
    <Container>
      <Row className="mt-4">
        <Col>
          <ListGroup style={{ height: '400px', overflowY: 'scroll' }}>
            {chatHistory.map((msg, index) => (
              <ListGroup.Item key={index} className={msg.sender === 'user' ? 'text-right' : ''}>
                <strong>{msg.sender}:</strong> {typeof msg.content === 'object' && msg.content !== null ? <pre>{JSON.stringify(msg.content, null, 2)}</pre> : msg.content}
              </ListGroup.Item>
            ))}
          </ListGroup>
        </Col>
      </Row>
      <Row className="mt-2">
        <Col>
          <Form onSubmit={(e) => { e.preventDefault(); sendMessage(); }}>
            <Form.Group className="d-flex">
              <Form.Control
                type="text"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Type your message..."
              />
              <Button variant="primary" type="submit">Send</Button>
            </Form.Group>
          </Form>
        </Col>
      </Row>
    </Container>
  );
};

export default Chat;
