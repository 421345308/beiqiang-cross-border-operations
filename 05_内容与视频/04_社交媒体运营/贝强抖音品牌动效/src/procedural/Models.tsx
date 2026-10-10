import React, {useMemo, useLayoutEffect, useRef} from 'react';
import * as THREE from 'three';
import {useThree} from '@react-three/fiber';
import {footGeometry, knitTexture, loft, loopGeometry, soleRings, upperRings} from './geometry';

export const Camera:React.FC<{position:[number,number,number]; target:[number,number,number]; zoom:number}> = ({position,target,zoom}) => {
  const {camera} = useThree();
  useLayoutEffect(()=> {camera.position.set(...position); camera.lookAt(...target); (camera as THREE.OrthographicCamera).zoom=zoom; camera.updateProjectionMatrix();},[camera,position[0],position[1],position[2],target[0],target[1],target[2],zoom]);
  return null;
};

export const Shoe:React.FC<{flare?:number; reveal?:number}> = ({flare=0,reveal=1})=> {
  const upper=useMemo(()=>loft(upperRings,112,128,true,flare),[flare]);
  const sole=useMemo(()=>loft(soleRings,32,128),[]);
  const texture=useMemo(knitTexture,[]);
  const band=useMemo(()=>loft([[1.94,-1.25,-.43,.38],[1.97,-1.27,-.41,.40],[2.01,-1.27,-.41,.40],[2.05,-1.25,-.43,.38]],8,96,false,flare),[flare]);
  useLayoutEffect(()=> {upper.setDrawRange(0,Math.floor(reveal*112)*128*6);},[upper,reveal]);
  return <group>
    <mesh geometry={sole}><meshStandardMaterial color="#202226" roughness={.66}/></mesh>
    <mesh geometry={upper}><meshStandardMaterial color="#d4d4d4" map={texture} bumpMap={texture} bumpScale={.012} roughness={.93} side={THREE.DoubleSide}/></mesh>
    {reveal>.98 && <>
      <mesh geometry={band}><meshStandardMaterial color="#292b2f" roughness={.8} side={THREE.DoubleSide}/></mesh>
      <mesh position={[-1.29,1.94,0]} rotation={[0,0,-.13]}><torusGeometry args={[.09,.025,8,28,Math.PI*1.9]}/><meshStandardMaterial color="#202226" roughness={.65}/></mesh>
    </>}
    {Array.from({length:16},(_,i)=><mesh key={i} position={[-1.30+i*.182,.083,0]} scale={[.012,.024,.53*(.62+.38*Math.sin((i+1)/17*Math.PI))]}><boxGeometry/><meshStandardMaterial color="#111315" roughness={.8}/></mesh>)}
  </group>;
};

export const Foot:React.FC<{entry?:boolean}> = ({entry=false})=> {
  const geo=useMemo(()=>entry?loft([[1.10,-1.08,-.56,.265],[1.7,-1.08,-.56,.28],[2.2,-1.10,-.55,.285],[3.3,-1.14,-.50,.32],[4.4,-1.19,-.46,.365]],70,80):footGeometry(),[entry]);
  return <mesh geometry={geo}><meshStandardMaterial color="#cabda4" roughness={.78}/></mesh>;
};

// The collar hides the interior foot; this is a stylized entry rig, not cloth physics.
export const WearingRig:React.FC<{progress:number}> = ({progress})=> {
  const geo=useMemo(footGeometry,[]);
  const original=useMemo(()=>new Float32Array(geo.getAttribute('position').array),[geo]);
  const clips=useMemo(()=>[new THREE.Plane(new THREE.Vector3(0,1,0),-2.035)],[]);
  const raised=1.25*(1-progress);
  useLayoutEffect(()=> {
    const attr=geo.getAttribute('position');
    for(let i=0;i<attr.count;i++) {
      const x=original[i*3],y=original[i*3+1],z=original[i*3+2];
      const t=Math.max(0,Math.min(1,(y-1.0)/.7));
      const weight=1-t*t*(3-2*t),angle=-1.15*(1-progress)*weight;
      const dx=x+.83,dy=y-1.1;
      attr.setXYZ(i,-.83+dx*Math.cos(angle)-dy*Math.sin(angle),1.1+dx*Math.sin(angle)+dy*Math.cos(angle)+raised,z);
    }
    attr.needsUpdate=true;geo.computeVertexNormals();
  },[geo,original,progress,raised]);
  return <mesh geometry={geo}><meshStandardMaterial color="#cabda4" roughness={.78} clippingPlanes={clips}/></mesh>;
};

export const KnitLoops:React.FC<{progress:number; turn:number}> = ({progress,turn})=> {
  const geometry=useMemo(loopGeometry,[]);
  const ref=useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(()=> {
    const dummy=new THREE.Object3D();
    for(let row=0;row<12;row++) for(let col=0;col<14;col++) {
      const n=row*14+col, p=Math.max(0,Math.min(1,progress*168-n));
      const x=(col-6.5)*.53, y=(row-5.5)*.77;
      dummy.position.set(x,y,Math.cos(x*.38)*.17);
      dummy.scale.setScalar(p); dummy.updateMatrix(); ref.current!.setMatrixAt(n,dummy.matrix);
      ref.current!.setColorAt(n,new THREE.Color(row%3===0?'#80715b':'#3e403e'));
    }
    ref.current!.instanceMatrix.needsUpdate=true;
    if(ref.current!.instanceColor)ref.current!.instanceColor.needsUpdate=true;
  },[progress]);
  return <group rotation={[.07,turn,0]}><instancedMesh ref={ref} args={[geometry,undefined,168]}><meshStandardMaterial color="white" roughness={.82} metalness={.06}/></instancedMesh></group>;
};

export const AssistHand:React.FC<{pull:number}> = ({pull}) => {
  const geometry=useMemo(()=> {
    const s=new THREE.Shape(); s.moveTo(-1.1,.25);s.lineTo(-.62,.25);
    s.bezierCurveTo(-.43,.35,-.26,.28,-.08,.15);s.lineTo(.12,.12);
    s.bezierCurveTo(.23,.12,.23,.01,.14,-.02);s.lineTo(-.10,-.03);
    s.bezierCurveTo(-.15,-.06,-.20,-.11,-.24,-.12);
    s.bezierCurveTo(-.11,-.16,.07,-.13,.11,-.20);
    s.bezierCurveTo(.16,-.29,.08,-.37,-.02,-.33);s.lineTo(-.35,-.23);
    s.bezierCurveTo(-.43,-.25,-.58,-.21,-.70,-.14);s.lineTo(-1.1,-.13);s.closePath();
    return new THREE.ExtrudeGeometry(s,{depth:.13,bevelEnabled:true,bevelSegments:4,steps:1,bevelSize:.045,bevelThickness:.045,curveSegments:24});
  },[]);
  return <mesh position={[-1.38,2.05+pull*.05,.13]} geometry={geometry}><meshStandardMaterial color="#cabda4" roughness={.8}/></mesh>;
};

export const Lights:React.FC=()=> <>
  <ambientLight intensity={.65}/><hemisphereLight args={['#fff6e8','#54483b',1.7]}/>
  <directionalLight position={[2,6,4]} intensity={3.5} color="#fff6e6"/>
  <directionalLight position={[-4,2,-3]} intensity={2.4} color="#dae4f3"/>
</>;
