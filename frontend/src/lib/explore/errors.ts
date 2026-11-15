/**
 * The backend answered, but has nothing for this spot. The message is written
 * for the user and shown as is; `suggestion` is somewhere that does have data.
 */
export class NoDataError extends Error {
  constructor(
    message: string,
    public suggestion?: { name: string; ra: number; dec: number; fov: number },
  ) {
    super(message);
    this.name = "NoDataError";
  }
}
