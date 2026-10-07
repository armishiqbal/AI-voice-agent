import {NextRequest,NextResponse} from "next/server";
export async function proxy(request:NextRequest,path:string){
 const base=(process.env.AWAAZ_API_URL||"http://127.0.0.1:8000").replace(/\/+$/,"");
 if(!/^[a-zA-Z0-9/_-]+$/.test(path))return NextResponse.json({detail:"Invalid path"},{status:400});
 if(!["GET","HEAD"].includes(request.method)&&request.headers.get("origin")!==request.nextUrl.origin)return NextResponse.json({detail:"Invalid origin"},{status:403});
 if(Number(request.headers.get("content-length")||0)>65536)return NextResponse.json({detail:"Request too large"},{status:413});
 const headers=new Headers({"content-type":"application/json"});
 for(const k of ["cookie","x-csrf-token"]) {const v=request.headers.get(k);if(v)headers.set(k,v);}
 // Origin has been validated against the public host; the internal API sees its own host.
 let body:string|undefined;
 if(!["GET","HEAD"].includes(request.method)){body=await request.text();if(new TextEncoder().encode(body).length>65536)return NextResponse.json({detail:"Request too large"},{status:413});}
 try{const r=await fetch(`${base}/v1/${path}${request.nextUrl.search}`,{method:request.method,headers,body,cache:"no-store",signal:AbortSignal.timeout(12000)});
 const output=new Headers({"content-type":r.headers.get("content-type")||"application/json","cache-control":"no-store"});for(const c of r.headers.getSetCookie())output.append("set-cookie",c);
 return new NextResponse(await r.text(),{status:r.status,headers:output});
 }catch{return NextResponse.json({detail:"The service is temporarily unavailable"},{status:502});}
}
