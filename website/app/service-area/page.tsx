import Link from "next/link";
import {agencies} from "@/lib/marketplace";
import {metadata} from "@/lib/site";
import styles from "@/components/Portal.module.css";
export const dynamic="force-dynamic";
export const generateMetadata=()=>metadata("Service areas","Coverage declared by approved agency profiles. Check published inventory in your location.","/service-area");
export default async function Page(){const orgs=await agencies().catch(()=>null),cities=[...new Set(orgs?.flatMap(o=>o.coverage)||[])];return <div className={styles.portal}><h1>Where we can help.</h1><p>Coverage comes from approved agency profiles. Published supply and viewing availability may vary by area.</p><div className={styles.links}>{cities.map(c=><Link key={c} href={`/properties?city=${encodeURIComponent(c)}`}>{c}</Link>)}</div>{!cities.length&&<p>{orgs?"Reviewed agency coverage is being prepared.":"Agency coverage is temporarily unavailable."}</p>}<Link href="/contact">Share your requirements →</Link></div>;}
