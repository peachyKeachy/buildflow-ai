import { useState } from "react";

function App() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");

  async function handleSend() {
    const response = await fetch("http://127.0.0.1:8000/ai/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: message,
      }),
    });

    const data = await response.json();

    setAnswer(data.answer);
  }

  return (
    <main>
      <h1>BuildFlow AI</h1>

      <p>Construction Operations Copilot</p>

      <input
        type="text"
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        placeholder="Ask about project RFIs..."
      />

      <button onClick={handleSend}>
        Send
      </button>

      <p>Current message: {message}</p>

      <p>BuildFlow response: {answer}</p>
    </main>
  );
}

export default App;