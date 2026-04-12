const express = require('express');
const app = express();

const port = process.env.PORT || 3000;
const dbUrl = process.env.DATABASE_URL;

app.get('/', (req, res) => {
  res.json({ message: 'Hello World' });
});

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
