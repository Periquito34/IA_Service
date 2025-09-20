export function errorHandler(err, req, res, _next) {
  // log mínimo
  console.error('[ERROR]', err);
  const status = err.status || 500;
  res.status(status).json({
    error: err.message || 'Internal Server Error'
  });
}
