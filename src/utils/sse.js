export function initSSE(res) {
  res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no'); // útil si hay Nginx
  res.flushHeaders?.();

  const send = (dataObj) => {
    res.write(`data: ${JSON.stringify(dataObj)}\n\n`);
  };

  const event = (eventName, dataObj = {}) => {
    res.write(`event: ${eventName}\n`);
    res.write(`data: ${JSON.stringify(dataObj)}\n\n`);
  };

  // keepalive
  const ka = setInterval(() => res.write(': ping\n\n'), 15000);

  const close = () => {
    clearInterval(ka);
    res.end();
  };

  return { send, event, close };
}
