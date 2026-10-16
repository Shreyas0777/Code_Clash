# Integration

Import `DigitalTwinModule` from `src/DigitalTwinModule.tsx` into a parent React app. The module currently owns local selection state and uses only scoped component styling. To connect real data, replace the return shape in `src/data/api.ts` with an adapter for verified FastAPI schemas, preserving `Building` and campus units. Set `VITE_API_BASE_URL` through the host app environment.

The GLB URL is `/models/free_basic_campus_scene.glb`; copy it to the host's public assets when embedding. If future model inspection establishes building mesh names, replace the illustrative positions in `src/data/demo.ts` with a model-to-building mapping.
