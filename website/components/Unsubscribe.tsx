"use client";
import {useState} from "react";
import styles from "./Portal.module.css";
export function Unsubscribe({token}:{token:string}){const [status,setStatus]=useState("");return <section className={styles.portal}><h1>Stop these property alerts.</h1><p>This stops the matching subscription, including alerts still queued for delivery.</p><button onClick={async()=>{try{const r=await fetch("/api/unsubscribe",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({token})});setStatus(r.ok?"You are unsubscribed.":"This unsubscribe link is invalid. You can also manage alerts in your account.");}catch{setStatus("The service is unavailable. Please retry.");}}}>Unsubscribe</button><p role="status">{status}</p></section>;}
