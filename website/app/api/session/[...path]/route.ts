import {NextRequest,NextResponse} from "next/server";
import {proxy} from "@/lib/proxy";
async function handler(r:NextRequest,{params}:{params:Promise<{path:string[]}>}){
 const parts=(await params).path;
 if(!["auth","me","agency","staff"].includes(parts[0]))return NextResponse.json({detail:"Invalid route"},{status:404});
 return proxy(r,parts.join("/"));
}
export const GET=handler,POST=handler,PATCH=handler,DELETE=handler;
