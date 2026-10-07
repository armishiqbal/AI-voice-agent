import {LocationLanding,cities} from "@/components/LocationLanding";
import {metadata} from "@/lib/site";
export const dynamic="force-dynamic";
type Params={city:string;area?:string};
export async function generateMetadata({params}:{params:Promise<Params>}){const p=await params;return {...metadata(`Properties in ${cities[p.city]||p.city}`,"Explore published inventory and reviewed local property information.",`/rent/${p.city}${p.area?`/${p.area}`:""}`),...(!p.area?{robots:{index:false,follow:true}}:{})};}
export default async function Page({params}:{params:Promise<Params>}){const p=await params;return <LocationLanding {...p} transaction="rent"/>;}
