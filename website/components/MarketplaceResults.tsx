"use client";
import {useEffect,useState} from "react";
import dynamic from "next/dynamic";
import {ListingCard} from "./ListingCard";
import {type Listing,type SearchParams} from "@/lib/catalog";
import styles from "./Portal.module.css";
const PropertyMap=dynamic(()=>import("./PropertyMap").then(m=>m.PropertyMap),{ssr:false,loading:()=> <p role="status">Loading map…</p>});
export function MarketplaceResults({properties,params}:{properties:Listing[];params:SearchParams}){
 const [showMap,setShowMap]=useState(false);
 useEffect(()=>{setShowMap(window.matchMedia("(min-width:1024px)").matches);},[]);
 return <><button aria-pressed={showMap} onClick={()=>setShowMap(!showMap)}>{showMap?"List only":"List and map"}</button><div className={showMap?styles.workspace:undefined}><div className={styles.grid} style={{gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,280px),1fr))"}}>{properties.map(p=><ListingCard key={p.id} property={p}/>)}</div>{showMap&&<PropertyMap params={params}/>}</div></>;
}
