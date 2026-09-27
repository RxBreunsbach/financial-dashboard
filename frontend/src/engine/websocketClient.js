const WS_URL = "ws://localhost:8000/ws";

/** Fans out server push messages (keyed by series_id) to any number of subscribed callbacks. */
export class WebSocketClient {
  constructor() {
    this._listeners = new Map(); // series_id -> Set<callback>
    this._socket = null;
    this._connectPromise = null;
  }

  _ensureConnected() {
    if (this._socket && this._socket.readyState === WebSocket.OPEN) {
      return Promise.resolve(this._socket);
    }
    if (this._connectPromise) return this._connectPromise;

    this._connectPromise = new Promise((resolve, reject) => {
      const socket = new WebSocket(WS_URL);
      socket.addEventListener("open", () => resolve(socket));
      socket.addEventListener("error", (event) => reject(event));
      socket.addEventListener("message", (event) => {
        const message = JSON.parse(event.data);
        for (const callback of this._listeners.get(message.series_id) ?? []) {
          callback(message);
        }
      });
      socket.addEventListener("close", () => {
        this._socket = null;
        this._connectPromise = null;
      });
      this._socket = socket;
    });
    return this._connectPromise;
  }

  /** Subscribes to live updates for `seriesId`. Returns an unsubscribe function. */
  async subscribe(seriesId, callback) {
    if (!this._listeners.has(seriesId))
      this._listeners.set(seriesId, new Set());
    this._listeners.get(seriesId).add(callback);

    const socket = await this._ensureConnected();
    socket.send(JSON.stringify({ action: "subscribe", series_id: seriesId }));

    return () => this.unsubscribe(seriesId, callback);
  }

  unsubscribe(seriesId, callback) {
    const callbacks = this._listeners.get(seriesId);
    if (!callbacks) return;
    callbacks.delete(callback);
    if (callbacks.size === 0) {
      this._listeners.delete(seriesId);
      this._socket?.send(
        JSON.stringify({ action: "unsubscribe", series_id: seriesId }),
      );
    }
  }
}
