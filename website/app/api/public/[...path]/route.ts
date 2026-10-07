import {NextRequest} from "next/server";
import {proxy} from "@/lib/proxy";
export async function GET(r:NextRequest,{params}:{params:Promise<{path:string[]}>}){return proxy(r,`public/${(await params).path.join("/")}`);}
