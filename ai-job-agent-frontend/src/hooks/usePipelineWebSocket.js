import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "../utils/constants";

const buildWsUrl = (path) => {
  const base = API_BASE_URL.replace(/^http/, "ws").replace(/\/api\/v1$/, "");
  return `${base}${path}`;
};

export const usePipelineWebSocket = (websocketPath, active = true) => {
  const [events, setEvents] = useState([]);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const statusRef = useRef("idle");
  const reconnectRef = useRef(null);
  const socketRef = useRef(null);

  const updateStatus = (nextStatus) => {
    statusRef.current = nextStatus;
    setStatus(nextStatus);
  };

  useEffect(() => {
    if (!websocketPath || !active) return undefined;

    const connect = () => {
      updateStatus("connecting");
      const socket = new WebSocket(buildWsUrl(websocketPath));
      socketRef.current = socket;
      socket.onopen = () => updateStatus("connected");
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data);
        setEvents((prev) => [...prev, event]);
        if (event.stage === "DONE") {
          setResult(event.data);
          updateStatus("done");
          socket.close();
        }
        if (event.stage === "ERROR") updateStatus("error");
      };
      socket.onclose = () => {
        if (!["done", "error"].includes(statusRef.current)) {
          updateStatus("reconnecting");
          reconnectRef.current = window.setTimeout(connect, 2500);
        }
      };
      socket.onerror = () => updateStatus("error");
    };

    connect();

    return () => {
      window.clearTimeout(reconnectRef.current);
      socketRef.current?.close();
    };
  }, [websocketPath, active]);

  return { events, result, status };
};
