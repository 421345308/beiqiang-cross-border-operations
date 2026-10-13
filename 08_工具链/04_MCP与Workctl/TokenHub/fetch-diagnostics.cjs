// Optional Node preload for diagnosing THCLI fetch failures.
// Never log URL, headers, request body, response body, or credentials.
const originalFetch = globalThis.fetch;
globalThis.fetch = async (...args) => {
  try {
    return await originalFetch(...args);
  } catch (error) {
    const causes = [];
    const visit = (cause) => {
      if (!cause || causes.length >= 8) return;
      causes.push({
        name: cause.name,
        code: cause.code,
        syscall: cause.syscall,
      });
      if (Array.isArray(cause.errors)) cause.errors.forEach(visit);
      visit(cause.cause);
    };
    visit(error);
    console.error('[THCLI network diagnostic]', JSON.stringify(causes));
    throw error;
  }
};
