# Project status

## Current scene scope

- The rendered scene now contains only `dia_aarschot.glb` and `sjca_aarschot_schaluin.glb`.
- Older SET and standalone-building assets remain in `public/models/` as preserved source files but are not loaded or rendered.
- The two active environment models are rotated from their verified Z-up source orientation, grounded, placed side by side, and framed by the Aarschot overview camera.

## Delivered
- Standalone Vite + TypeScript React application with Fluxora digital-twin shell.
- Supplied GLB copied into and loaded from public assets.
- Camera orbit/pan/zoom, visualization modes, building selection, information panels, charts, and scenario calculator.
- Deterministic demo mode, API health fallback, model-mapping disclosure, responsive non-3D information access.
- Daylight sky, fog, landscaped ground plane, bounded orbit camera, and soft directional shadows.
- Replaced generic translucent box overlays with direct selection of verified GLB groups: `mid_building`, `third_building`, `small_building`, and `parking_shade`.
- Added hover tooltip/tint, persistent selected-building tint, camera focus transition, and reset/deselect action.
- Added and loaded three supplied GLBs alongside the original SET asset: `124-87-117_building.glb`, `weathered_red_saltbox_farmhouse.glb`, and `classical_mansion_model_trellis_3d_vs_supavoxel.glb`.
- Normalized the extra assets from measured bounds and placed them as illustrative campus annexes: office west, farmhouse south-east, mansion north-east. All are selectable and camera-focusable, with explicitly labeled deterministic demo fixtures.
- Rebuilt the building identity layer to remove the former Engineering Block, Central Library, Research Labs, and Admin Centre labels. The complete seven-item assembly now uses consistent asset-based names and explicitly labeled deterministic demo fixtures.
- Added two full-environment GLBs: `dia_aarschot.glb` and `sjca_aarschot_schaluin.glb`. Both were verified as Z-up site models, rotated to Y-up, grounded from their measured Z minima, and placed as large adjoining environment sections beneath the campus assembly.

## Verification and limitations
- The included GLB has been located and its browser loading path is configured. Original mesh hierarchy and semantic building names have not been verified; selectable colored overlays are illustrative. Browser preview could not reach the isolated local development server, so visual runtime smoke testing remains a local next step.
- No backend source or API documentation was accessible, so no unverified endpoint/schema mapping is claimed.
- Run `npm run build` after dependency installation to verify the local environment.
- `npm run build` passed on 16 Oct 2026. It reports only the existing bundle-size advisory from Three.js and Recharts.
- The original model has a measured source extent of about 172 × 12 × 119 units. Its scene scale and overview camera were adjusted to frame the full assembly, avoiding the prior oversized-ground composition.
- `npm run build` passed after the environment addition. Browser rendering remains unverified in this chat because its isolated preview surface cannot access the desktop-local server.
