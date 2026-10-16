import { Canvas, useFrame, type ThreeEvent } from '@react-three/fiber';
import { ContactShadows, OrbitControls, Sky, useGLTF } from '@react-three/drei';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import type { Building, Mode } from '../types';

const coreGroups: Record<string, string> = { studio: 'small_building', canopy: 'parking_shade' };
const removedCoreGroups = ['mid_building', 'third_building'];
const fromGroup = Object.fromEntries(Object.entries(coreGroups).map(([id, name]) => [name, id]));
const focusPoints: Record<string, [number, number, number]> = {
  studio: [2.3, .42, .5], canopy: [.9, .35, 2.3],
  office: [-5.8, 1.55, 3.8], farmhouse: [0, .75, 3.8], mansion: [5.8, 1.05, 3.8],
};

const tint = (building: Building, mode: Mode) => {
  if (mode === 'anomaly') return building.anomaly ? '#e56a57' : '#7c8e96';
  if (mode === 'energy') return building.energy > 400 ? '#e6a34d' : '#35c4c2';
  if (mode === 'carbon') return building.carbon > 200 ? '#dc715e' : '#54b889';
  return '#39d4ce';
};

const parentId = (object: THREE.Object3D) => {
  let item: THREE.Object3D | null = object;
  while (item) { if (fromGroup[item.name]) return fromGroup[item.name]; item = item.parent; }
  return null;
};

function paint(scene: THREE.Group, building: Building | undefined, mode: Mode, active: boolean, hovered: boolean) {
  scene.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return;
    let material = object.material as THREE.MeshStandardMaterial;
    if (!material?.color) return;
    if (!material.userData.fluxoraPaint) { material = material.clone(); material.userData.fluxoraPaint = true; object.material = material; }
    if (!material.userData.base) material.userData.base = { color: material.color.clone(), emissive: material.emissive?.clone(), intensity: material.emissiveIntensity };
    const base = material.userData.base as { color: THREE.Color; emissive?: THREE.Color; intensity?: number };
    material.color.copy(base.color);
    if (material.emissive && base.emissive) material.emissive.copy(base.emissive);
    material.emissiveIntensity = base.intensity ?? 0;
    if (!building) return;
    const color = tint(building, mode);
    if (mode !== 'normal') {
      material.color.lerp(new THREE.Color(color), .42);
      if (material.emissive) { material.emissive.set(color); material.emissiveIntensity = active ? .38 : hovered ? .2 : .06; }
    } else if (material.emissive && (active || hovered)) { material.emissive.set('#32d2cb'); material.emissiveIntensity = active ? .34 : .14; }
  });
}

type InteractionProps = { buildings: Building[]; mode: Mode; selected: string | null; hovered: string | null; onSelect: (id: string) => void; onHover: (id: string | null) => void };

function OriginalCampus({ buildings, mode, selected, hovered, onSelect, onHover }: InteractionProps) {
  const asset = useGLTF('/models/free_basic_campus_scene.glb');
  const scene = useMemo(() => asset.scene.clone(true), [asset.scene]);
  const box = useMemo(() => new THREE.Box3().setFromObject(scene), [scene]);
  const center = useMemo(() => box.getCenter(new THREE.Vector3()), [box]);
  useEffect(() => {
    removedCoreGroups.forEach((name) => {
      const group = scene.getObjectByName(name);
      if (group) group.visible = false;
    });
    Object.keys(coreGroups).forEach((id) => {
      const group = scene.getObjectByName(coreGroups[id]) as THREE.Group | undefined;
      if (group) paint(group, buildings.find((building) => building.id === id), mode, selected === id, hovered === id);
    });
  }, [buildings, hovered, mode, scene, selected]);
  return <group scale={.065} position={[-center.x * .065, -box.min.y * .065, -center.z * .065]}>
    <primitive object={scene}
      onPointerMove={(event: ThreeEvent<PointerEvent>) => { event.stopPropagation(); const id = parentId(event.object); if (id && hovered !== id) onHover(id); }}
      onPointerOut={(event: ThreeEvent<PointerEvent>) => { event.stopPropagation(); onHover(null); }}
      onClick={(event: ThreeEvent<MouseEvent>) => { event.stopPropagation(); const id = parentId(event.object); if (id) onSelect(id); }} />
  </group>;
}

type AddonProps = Omit<InteractionProps, 'buildings'> & { url: string; id: string; position: [number, number, number]; height: number; building: Building };
function Addon({ url, id, position, height, building, mode, selected, hovered, onSelect, onHover }: AddonProps) {
  const asset = useGLTF(url);
  const scene = useMemo(() => asset.scene.clone(true), [asset.scene]);
  const box = useMemo(() => new THREE.Box3().setFromObject(scene), [scene]);
  const scale = height / (box.max.y - box.min.y);
  const center = useMemo(() => box.getCenter(new THREE.Vector3()), [box]);
  useEffect(() => paint(scene, building, mode, selected === id, hovered === id), [building, hovered, id, mode, scene, selected]);
  return <group position={position}><group position={[-center.x * scale, -box.min.y * scale, -center.z * scale]} scale={scale}>
    <primitive object={scene}
      onPointerMove={(event: ThreeEvent<PointerEvent>) => { event.stopPropagation(); if (hovered !== id) onHover(id); }}
      onPointerOut={(event: ThreeEvent<PointerEvent>) => { event.stopPropagation(); onHover(null); }}
      onClick={(event: ThreeEvent<MouseEvent>) => { event.stopPropagation(); onSelect(id); }} />
  </group></group>;
}

function AssetMarker({ building, mode, active, hovered }: { building: Building; mode: Mode; active: boolean; hovered: boolean }) {
  const point = focusPoints[building.id];
  if (!point || (!active && !hovered)) return null;
  const color = mode === 'normal' ? '#49e0d7' : tint(building, mode);
  return <mesh position={[point[0], .035, point[2]]} rotation={[-Math.PI / 2, 0, 0]}>
    <ringGeometry args={[active ? .68 : .48, active ? .74 : .54, 40]} />
    <meshBasicMaterial color={color} transparent opacity={active ? .96 : .68} side={THREE.DoubleSide} />
  </mesh>;
}

function CampusLandscape({ clear }: { clear: () => void }) {
  return <group>
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -.08, 0]} receiveShadow onPointerMove={clear}><planeGeometry args={[32, 32]} /><meshStandardMaterial color="#426f51" roughness={1} /></mesh>
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -.068, 1.3]} receiveShadow><planeGeometry args={[16.5, 10.5]} /><meshStandardMaterial color="#73856c" roughness={.96} /></mesh>
    <mesh rotation={[-Math.PI / 2, 0, Math.PI / 2]} position={[0, -.052, -.6]} receiveShadow><planeGeometry args={[.62, 20]} /><meshStandardMaterial color="#42565a" roughness={.94} /></mesh>
    {[-5.8, 0, 5.8].map((x) => <mesh key={x} rotation={[-Math.PI / 2, 0, 0]} position={[x, -.046, 3.8]} receiveShadow><circleGeometry args={[2.15, 40]} /><meshStandardMaterial color="#84907c" roughness={.9} /></mesh>)}
  </group>;
}

function Camera({ selected, resetKey }: { selected: string | null; resetKey: number }) {
  const controls = useRef<OrbitControlsImpl>(null);
  const goal = useRef(new THREE.Vector3(15, 10, 17));
  const target = useRef(new THREE.Vector3(0, .7, 0));
  useEffect(() => {
    const focus = selected ? focusPoints[selected] : undefined;
    target.current.set(focus?.[0] ?? 0, focus?.[1] ?? .7, focus?.[2] ?? 0);
    goal.current.copy(target.current).add(focus ? new THREE.Vector3(5.8, 4.2, 5.8) : new THREE.Vector3(15, 10, 17));
  }, [selected, resetKey]);
  useFrame(({ camera }) => { if (!controls.current) return; camera.position.lerp(goal.current, .065); controls.current.target.lerp(target.current, .075); controls.current.update(); });
  return <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={.09} minDistance={3} maxDistance={30} maxPolarAngle={Math.PI / 2.06} target={[0, .7, 0]} />;
}

export function CampusScene({ buildings, mode, selected, onSelect, resetKey }: { buildings: Building[]; mode: Mode; selected: string | null; onSelect: (id: string) => void; resetKey: number }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const get = (id: string) => buildings.find((building) => building.id === id)!;
  const activeBuilding = buildings.find((building) => building.id === (hovered ?? selected));
  const clear = () => setHovered(null);
  return <div className="scene" aria-label="Interactive Fluxora campus">
    <Canvas shadows camera={{ position: [15, 10, 17], fov: 40, near: .1, far: 100 }} dpr={[1, 1.5]} onPointerMissed={clear} onCreated={({ gl, scene }) => { gl.setClearColor('#9ad3df'); gl.shadowMap.enabled = true; gl.shadowMap.type = THREE.PCFSoftShadowMap; scene.fog = new THREE.Fog('#b8dce0', 22, 56); }}>
      <Sky distance={450000} sunPosition={[55, 32, 18]} inclination={.58} azimuth={.2} />
      <hemisphereLight args={['#e0f7ff', '#3d6041', 2.1]} /><directionalLight position={[16, 25, 12]} intensity={2.3} castShadow shadow-mapSize-width={1024} shadow-mapSize-height={1024} />
      <CampusLandscape clear={clear} />
      <Suspense fallback={null}><OriginalCampus buildings={buildings} mode={mode} selected={selected} hovered={hovered} onSelect={onSelect} onHover={setHovered} />
        <Addon url="/models/124-87-117_building.glb" id="office" position={[-5.8, 0, 3.8]} height={3.35} building={get('office')} mode={mode} selected={selected} hovered={hovered} onSelect={onSelect} onHover={setHovered} />
        <Addon url="/models/weathered_red_saltbox_farmhouse.glb" id="farmhouse" position={[0, 0, 3.8]} height={2.05} building={get('farmhouse')} mode={mode} selected={selected} hovered={hovered} onSelect={onSelect} onHover={setHovered} />
        <Addon url="/models/classical_mansion_model_trellis_3d_vs_supavoxel.glb" id="mansion" position={[5.8, 0, 3.8]} height={2.75} building={get('mansion')} mode={mode} selected={selected} hovered={hovered} onSelect={onSelect} onHover={setHovered} /></Suspense>
      {buildings.map((building) => <AssetMarker key={building.id} building={building} mode={mode} active={selected === building.id} hovered={hovered === building.id} />)}
      <ContactShadows position={[0, -.04, 0]} opacity={.32} scale={24} blur={2.8} far={15} /><Camera selected={selected} resetKey={resetKey} />
    </Canvas>
    {activeBuilding && <div className="building-tooltip"><strong>{activeBuilding.name}</strong><span>{hovered ? 'Click to inspect simulated data' : 'Selected asset'}</span></div>}
    <div className="scene-label">Interactive assembly · drag to orbit · scroll to zoom</div>
  </div>;
}

useGLTF.preload('/models/free_basic_campus_scene.glb');
useGLTF.preload('/models/124-87-117_building.glb');
useGLTF.preload('/models/weathered_red_saltbox_farmhouse.glb');
useGLTF.preload('/models/classical_mansion_model_trellis_3d_vs_supavoxel.glb');
