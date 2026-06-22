import { useCallback, useEffect, useRef, useState } from "react";

export const useAsync = (request, deps = [], options = {}) => {
  const requestRef = useRef(request);
  const depsKey = JSON.stringify(deps);
  const [data, setData] = useState(options.initialData ?? null);
  const [loading, setLoading] = useState(Boolean(options.immediate ?? true));
  const [error, setError] = useState(null);

  useEffect(() => {
    requestRef.current = request;
  });

  const execute = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    try {
      const result = await requestRef.current(...args);
      setData(result);
      return result;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (options.immediate === false) return;
    queueMicrotask(() => {
      execute().catch(() => {});
    });
  }, [execute, options.immediate, depsKey]);

  return { data, loading, error, execute, setData };
};
