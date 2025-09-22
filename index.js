import app from './src/app.js';
import { config } from './src/config/env.js';

app.listen(config.port, () => {
  console.log(`AI Service listening on :${config.port}`);
});
