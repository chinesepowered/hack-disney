# Tools notes

- Custom tools (dispute data, Band case room, vault, processor) run in the merchant's backend. They return
  JSON; photos come back as images for you to inspect.
- Exhibit ids look like `EX-1042-B`. They are the only valid citations.
- The sandbox has Python 3.12 with reportlab. Work under `/workspace/cases/<ID>/`.
- `artifact_publish` takes the absolute path of the PDF. Pass that same path to `check_packet` and
  `submit_evidence`.
- `submit_evidence` and `accept_dispute` wait for the merchant's approval; that is expected.
