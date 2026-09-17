import { useState } from "react";

function App() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSend() {
    if (!message.trim()) {
      setError("Please enter a question.");
      setAnswer("");
      return;
    }
    setLoading(true);
    setError("");
    setAnswer("");

    try {
      const response = await fetch("http://127.0.0.1:8000/ai/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: message,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();

      setAnswer(data.answer);
    } catch (error) {
      console.error(error);

      setError("Unable to reach BuildFlow. Please try again.");
    } finally {
      setLoading(false);
    }
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

      <button
        onClick={handleSend}
        disabled={loading || !message.trim()}
      >
        {loading ? "Thinking..." : "Send"}
      </button>

      {loading && <p>BuildFlow is thinking...</p>}

      {error && <p>{error}</p>}

      {answer && <p>BuildFlow response: {answer}</p>}
    </main>
  );
}

export default App;