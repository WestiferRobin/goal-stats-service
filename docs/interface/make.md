# Make interface

The public interface intentionally has five targets:

| Command | Contract |
| --- | --- |
| `make setup` | Check tools, create missing `.env.local`, and build images; start nothing |
| `make run` | Start providers, migrate, import bundled data, and start the API |
| `make test` | Run quality checks and isolated unit/integration tests |
| `make stop` | Stop local containers; preserve database data |
| `make help` | Display only this public interface |

Run all commands from the repository root. There is one local mode and one developer
configuration file. Compose and maintenance scripts remain internal mechanisms.
