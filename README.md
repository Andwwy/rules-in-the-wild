# Rules in the Wild

Local labeling UI for the rules pipeline. Connects to the shared MotherDuck DB.

## Run it

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Create a `.env` file in this directory with a MotherDuck token (get one at https://app.motherduck.com → Settings → Service Tokens):

   ```
   MOTHERDUCK_TOKEN=eyJhbGc...your_token...
   ```

3. Start it:

   ```bash
   docker compose up --build
   ```

4. Open http://localhost:5173.

`Ctrl-C` to stop. `docker compose down` to clean up.
