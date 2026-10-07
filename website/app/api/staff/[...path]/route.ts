import { NextRequest, NextResponse } from "next/server";
import {proxy} from "@/lib/proxy";
async function handler(r:NextRequest,{params}:{params:Promise<{path:string[]}>}){
 const path=(await params).path.join("/");
 if(process.env.NODE_ENV!=="development"||process.env.AWAAZ_DEV_STAFF_TOOLS!=="true")return proxy(r,`staff/${path}`);
 if(!/^[a-zA-Z0-9/_-]+$/.test(path))return NextResponse.json({detail:"Invalid path"},{status:400});
 if(!["GET","HEAD"].includes(r.method)&&r.headers.get("origin")!==r.nextUrl.origin)return NextResponse.json({detail:"Invalid origin"},{status:403});
 const text=["GET","HEAD"].includes(r.method)?undefined:await r.text();if(text&&text.length>65536)return NextResponse.json({detail:"Too large"},{status:413});
 try{const response=await fetch(`${process.env.AWAAZ_API_URL||"http://127.0.0.1:8000"}/v1/staff/${path}${r.nextUrl.search}`,{method:r.method,headers:{authorization:r.headers.get("authorization")||"","content-type":"application/json"},body:text,signal:AbortSignal.timeout(12000)});return new NextResponse(await response.text(),{status:response.status,headers:{"content-type":"application/json"}});}catch{return NextResponse.json({detail:"Staff service unavailable"},{status:502});}
}
export const GET=handler,POST=handler,PATCH=handler,PUT=handler,DELETE=handler;
