/**
 * Lets api/client.ts announce "the login has expired" without importing
 * AuthContext directly - AuthContext imports the client, so that would create
 * a loop between the two files.
 *
 * Only one listener is kept, because there's only ever one AuthProvider. In
 * React's development mode it signs up twice; the second replaces the first,
 * and the first one's clean-up then does nothing.
 */
type Handler = () => void;

let handler: Handler | null = null;

export function onUnauthorized(next: Handler): () => void {
  handler = next;
  return () => {
    if (handler === next) handler = null;
  };
}

export function emitUnauthorized(): void {
  handler?.();
}
