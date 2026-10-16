# Fluxora Digital Twin

> Current viewer scope: the two Aarschot full-environment models only. Earlier model assets are preserved locally but are not rendered.

Independent React/Three.js Digital Twin module for campus energy demonstrations. It loads the supplied `free_basic_campus_scene.glb` from `public/models/` and provides deterministic, visibly simulated energy intelligence.

## Run

```powershell
npm install
npm run dev
```

Use `npm run build` for a production check. Copy `.env.example` to `.env` only when configuring an API origin.

## Data honesty

The current UI is in demo mode. Values and building overlays are deterministic illustrative data, never real campus telemetry. `src/data/api.ts` performs a health check when `VITE_API_BASE_URL` is configured; a verified route/schema adapter must be added before presenting live values.

## Model

The supplied 615,536-byte GLB is integrated at `public/models/free_basic_campus_scene.glb`. It is loaded with Drei's GLTF loader against a procedural daylight sky and landscaped ground. The GLB hierarchy was inspected: selection maps directly to its named `mid_building`, `third_building`, `small_building`, and `parking_shade` groups; data labels remain illustrative demo mappings.

## Multi-model assembly

The scene also loads three independently selectable, normalized assets from `public/models/`: `124-87-117_building.glb` (west office annex), `weathered_red_saltbox_farmhouse.glb` (south-east farmhouse), and `classical_mansion_model_trellis_3d_vs_supavoxel.glb` (north-east mansion). Their positions are illustrative because no real-world placement metadata was supplied. Selecting any asset focuses the shared camera. The seven selectable assets have deterministic, explicitly simulated fixtures for demonstration only; none represents live or verified building telemetry. Use the reset control to return to the campus overview.

Two additional full-site environment models—`dia_aarschot.glb` and `sjca_aarschot_schaluin.glb`—form the broad visible site context. Both source files use Z-up coordinates; the scene rotates them to Three.js Y-up, grounds them at their measured bases, and uses a larger overview camera so they remain clearly visible rather than appearing as small props.
