"use client";
import {useEffect,useRef,useState} from "react";
import type {Map as MapType,GeoJSONSource} from "maplibre-gl";
import {useRouter} from "next/navigation";
import {catalogQuery,type SearchParams} from "@/lib/catalog";
import styles from "./Portal.module.css";
import "maplibre-gl/dist/maplibre-gl.css";
export function PropertyMap({params}:{params:SearchParams}){
 const holder=useRef<HTMLDivElement>(null),map=useRef<MapType|null>(null);
 const [message,setMessage]=useState("Preparing map…"),[selected,setSelected]=useState<{slug:string;title:string}|null>(null);
 const router=useRouter(),query=catalogQuery(params).toString();
 const [bounds,setBounds]=useState<string>("");
 useEffect(()=>{
  const key=process.env.NEXT_PUBLIC_MAPTILER_KEY;
  if(!key||process.env.NEXT_PUBLIC_MAP_ENABLED!=="true"){setMessage("Map search is not configured. List search remains available.");return;}
  let active=true;let controller:AbortController|undefined;
  import("maplibre-gl").then((ml)=>{
   if(!active||!holder.current)return;
   const m=new ml.Map({container:holder.current,style:`https://api.maptiler.com/maps/streets-v2/style.json?key=${encodeURIComponent(key)}`,center:({Islamabad:[73.06,33.69],Rawalpindi:[73.04,33.6],Lahore:[74.35,31.55],Karachi:[67.01,24.86]} as Record<string,[number,number]>)[new URLSearchParams(query).get("city")||""]||[73.06,33.69],zoom:10});map.current=m;
   const applied=new URLSearchParams(query);const coordinates=["west","south","east","north"].map(k=>Number(applied.get(k)));
   if(["west","south","east","north"].every(k=>applied.has(k))&&coordinates.every(Number.isFinite))m.fitBounds([[coordinates[0],coordinates[1]],[coordinates[2],coordinates[3]]],{duration:0,padding:20});
   m.addControl(new ml.NavigationControl());
   async function load(){controller?.abort();controller=new AbortController();const b=m.getBounds();const q=new URLSearchParams(query);q.delete("page");q.delete("page_size");q.set("west",String(b.getWest()));q.set("east",String(b.getEast()));q.set("south",String(b.getSouth()));q.set("north",String(b.getNorth()));q.set("zoom",String(Math.round(m.getZoom())));
    try{const r=await fetch(`/api/public/listings/map?${q}`,{signal:controller.signal});if(!r.ok)throw Error();const data=await r.json();if(!active)return;
     const src=m.getSource("properties") as GeoJSONSource|undefined;if(src)src.setData(data);else{m.addSource("properties",{type:"geojson",data});m.addLayer({id:"properties",type:"circle",source:"properties",paint:{"circle-radius":["case",["get","cluster"],20,10],"circle-color":"#18523c","circle-stroke-width":2,"circle-stroke-color":"white"}});m.addLayer({id:"labels",type:"symbol",source:"properties",layout:{"text-field":["case",["get","cluster"],["to-string",["get","count"]],["concat","PKR ",["to-string",["get","price_pkr"]]]],"text-size":12,"text-offset":[0,1.8]},paint:{"text-color":"#16251e","text-halo-color":"white","text-halo-width":2}});}
     setMessage(`${data.matching_viewport} matching properties in this area${data.truncated?"; zoom in to see more":""}. ${data.unmapped_count} matching listings have no approved coordinates and remain in list search.`);
    }catch(e){if(e instanceof DOMException&&e.name==="AbortError")return;setMessage("Map data is unavailable. Continue using list search.");}
   }
   m.on("load",()=>{void load();});m.on("moveend",()=>{const b=m.getBounds();const q=new URLSearchParams(query);q.delete("page");for(const [k,v] of Object.entries({west:b.getWest(),east:b.getEast(),south:b.getSouth(),north:b.getNorth()}))q.set(k,String(v));setBounds(q.toString());void load();});
   m.on("click","properties",(e)=>{const f=e.features?.[0];if(!f)return;if(f.properties.cluster){m.easeTo({center:e.lngLat,zoom:m.getZoom()+2,duration:window.matchMedia("(prefers-reduced-motion: reduce)").matches?0:300});void load();}else setSelected({slug:String(f.properties.slug),title:String(f.properties.title)});});
   m.on("error",()=>setMessage("Map provider is unavailable. List search remains available."));
  }).catch(()=>setMessage("Map could not load. Continue using list search."));
  return()=>{active=false;controller?.abort();map.current?.remove();map.current=null;};
 },[query]);
 return <section aria-label="Property map"><p role="status">{message}</p>{bounds&&<button onClick={()=>router.push(`/properties?${bounds}`)}>Search this area</button>}<div ref={holder} className={styles.map}/>{selected&&<a href={`/properties/${encodeURIComponent(selected.slug)}`}>{selected.title} → View property</a>}</section>;
}
