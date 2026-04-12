import { useEffect, useState } from 'react';

interface HealthStatus {
  status: string;
  timestamp: string;
}

export default function Home() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch((err) => setError(err.message));
  }, []);

  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui' }}>
      <h1>Mock Frontend</h1>
      <p>This is a sample Next.js application for testing OpenOps.</p>
      
      <h2>Backend Status</h2>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {health && (
        <div>
          <p>Status: {health.status}</p>
          <p>Timestamp: {health.timestamp}</p>
        </div>
      )}
      {!health && !error && <p>Loading...</p>}
    </main>
  );
}
