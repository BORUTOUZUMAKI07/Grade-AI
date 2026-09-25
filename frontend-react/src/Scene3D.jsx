import React, { useMemo, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Float, Stars, Html, Line } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';

const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* Calm ambient scene: faint stars and two slow wireframe solids that follow the pointer */
function Drift({ palette }) {
  const g = useRef();
  useFrame(({ pointer }, dt) => {
    g.current.rotation.y += dt * 0.03;
    g.current.rotation.x = THREE.MathUtils.lerp(g.current.rotation.x, pointer.y * 0.2, 0.03);
    g.current.position.x = THREE.MathUtils.lerp(g.current.position.x, pointer.x * 0.6, 0.03);
  });
  return (
    <group ref={g}>
      <Stars radius={45} depth={35} count={1400} factor={2.5} fade speed={0.5} />
      <Float speed={1.4} rotationIntensity={0.6} floatIntensity={1.2}>
        <mesh position={[4, 1, -6]}><icosahedronGeometry args={[2.2, 1]} /><meshBasicMaterial color={palette.accent} wireframe transparent opacity={0.12} /></mesh>
      </Float>
      <Float speed={1.1} floatIntensity={1.6}>
        <mesh position={[-5, -2, -8]}><torusKnotGeometry args={[1.2, 0.3, 120, 16]} /><meshBasicMaterial color={palette.accent2} wireframe transparent opacity={0.1} /></mesh>
      </Float>
    </group>
  );
}

export function Backdrop({ palette }) {
  return (
    <Canvas camera={{ position: [0, 0, 10], fov: 55 }} dpr={[1, 1.5]} frameloop={reduced() ? 'demand' : 'always'}
      eventSource={document.body} eventPrefix="client" gl={{ antialias: false, alpha: true }}>
      <Drift palette={palette} />
    </Canvas>
  );
}

/* 3D search space: x = study hours, y = attendance, z = previous marks */
const S = 4;
const pos = (p) => [Math.min(p.x / 12, 1) * S - S / 2, (p.y / 100) * S - S / 2, (p.z / 100) * S - S / 2];

function Dot({ p, palette }) {
  const [hover, setHover] = useState(false);
  const pass = p.result === 'Pass';
  const c = pass ? palette.pass : palette.fail;
  return (
    <mesh position={pos(p)} scale={hover ? 1.7 : 1} onPointerOver={(e) => { e.stopPropagation(); setHover(true); }} onPointerOut={() => setHover(false)}>
      {pass ? <sphereGeometry args={[0.07, 20, 20]} /> : <octahedronGeometry args={[0.09]} />}
      <meshStandardMaterial color={c} emissive={c} emissiveIntensity={0.5} />
      {hover && (
        <Html distanceFactor={7} style={{ pointerEvents: 'none' }}>
          <div className="whitespace-nowrap rounded-xl border border-white/10 bg-black/80 px-3 py-2 text-[11px] text-white backdrop-blur-md">
            {p.x}h · {p.y}% · {p.z} marks · {p.result}
          </div>
        </Html>
      )}
    </mesh>
  );
}

/* The student being predicted, joined to the 5 most similar records */
function Me({ me, points, palette }) {
  const ref = useRef();
  const target = useMemo(() => pos(me), [me]);
  const near = useMemo(() => {
    const t = new THREE.Vector3(...target);
    return points.map((p) => ({ p, d: new THREE.Vector3(...pos(p)).distanceTo(t) })).sort((a, b) => a.d - b.d).slice(0, 5);
  }, [points, target]);
  useFrame(({ clock }) => { if (ref.current && !reduced()) ref.current.scale.setScalar(1 + Math.sin(clock.elapsedTime * 3) * 0.18); });
  return (
    <group>
      <mesh ref={ref} position={target}>
        <sphereGeometry args={[0.13, 24, 24]} />
        <meshStandardMaterial color={palette.accent} emissive={palette.accent} emissiveIntensity={1} />
      </mesh>
      {near.map(({ p }, i) => <Line key={i} points={[target, pos(p)]} color={palette.accent} lineWidth={1} transparent opacity={0.55} dashed dashSize={0.1} gapSize={0.07} />)}
      <Html position={[target[0], target[1] + 0.32, target[2]]} center style={{ pointerEvents: 'none' }}>
        <span className="whitespace-nowrap rounded-full bg-black/75 px-2 py-0.5 text-[10px] text-white">This student</span>
      </Html>
    </group>
  );
}

function Axes({ palette }) {
  const box = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(S, S, S)), []);
  const h = S / 2;
  const axis = (b, label, at) => (
    <group>
      <Line points={[[-h, -h, -h], b]} color={palette.accent} lineWidth={1.2} />
      <Html position={at} center style={{ pointerEvents: 'none' }}><span className="text-[10px] text-neutral-400">{label}</span></Html>
    </group>
  );
  return (
    <>
      <lineSegments geometry={box}><lineBasicMaterial color={palette.accent} transparent opacity={0.15} /></lineSegments>
      {axis([h, -h, -h], 'Study hours →', [h + 0.45, -h, -h])}
      {axis([-h, h, -h], 'Attendance ↑', [-h, h + 0.3, -h])}
      {axis([-h, -h, h], 'Marks', [-h, -h, h + 0.3])}
    </>
  );
}

export function Cube3D({ points, palette, me }) {
  return (
    <Canvas camera={{ position: [5, 3.5, 5.5], fov: 50 }} dpr={[1, 2]}>
      <ambientLight intensity={0.7} />
      <pointLight position={[6, 6, 6]} intensity={35} />
      {points.map((p) => <Dot key={p.id} p={p} palette={palette} />)}
      {me && <Me me={me} points={points} palette={palette} />}
      <Axes palette={palette} />
      <OrbitControls enablePan={false} autoRotate={!reduced()} autoRotateSpeed={0.7} minDistance={4} maxDistance={12} />
      <EffectComposer><Bloom intensity={0.35} luminanceThreshold={0.6} mipmapBlur /></EffectComposer>
    </Canvas>
  );
}
