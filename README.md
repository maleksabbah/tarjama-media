# tarjama-media

Media worker for the **Tarjama** Arabic ASR platform. A Kafka consumer that extracts and prepares audio from uploaded video with ffmpeg, stores the result in object storage, and publishes the next task in the pipeline.

## Architecture

A worker rather than an API, but layered along the same lines:

- **Consumer / entrypoint** — subscribes to its Kafka topic and hands each message to the service layer.
- **Services** — the processing logic (audio extraction, chunking) and deciding what to publish next.
- **Repositories** — wrap object storage and the Kafka producer behind clean interfaces.
- **Config** — Kafka, object storage, and environment wiring.

Keeping the messaging and storage behind repositories means the processing logic stays focused on media handling, not infrastructure.

Part of a multi-service system — see the [platform overview](https://github.com/maleksabbah/tarjama-docker) for the full architecture, pipeline flow, and the other services.
