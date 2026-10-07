import {NextRequest,NextResponse} from "next/server";
export async function POST(r:NextRequest,{params}:{params:Promise<{organizationId:string;propertyId:string}>}){
 if(r.headers.get("origin")!==r.nextUrl.origin)return NextResponse.json({detail:"Invalid origin"},{status:403});
 if(Number(r.headers.get("content-length")||0)>8388608)return NextResponse.json({detail:"Photo too large"},{status:413});
 const p=await params;if(![p.organizationId,p.propertyId].every(v=>/^[a-zA-Z0-9-]+$/.test(v)))return NextResponse.json({detail:"Invalid path"},{status:400});
 const chunks:Uint8Array[]=[];let size=0;const reader=r.body?.getReader();if(!reader)return NextResponse.json({detail:"Photo required"},{status:422});
 for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>8388608){await reader.cancel();return NextResponse.json({detail:"Photo too large"},{status:413});}chunks.push(value);}
 const body=new Uint8Array(size);let offset=0;for(const chunk of chunks){body.set(chunk,offset);offset+=chunk.length;}
 try{const response=await fetch(`${process.env.AWAAZ_API_URL||"http://127.0.0.1:8000"}/v1/agency/${p.organizationId}/listings/${p.propertyId}/media`,{method:"POST",headers:{cookie:r.headers.get("cookie")||"","x-csrf-token":r.headers.get("x-csrf-token")||"","content-type":r.headers.get("content-type")||"application/octet-stream"},body,signal:AbortSignal.timeout(30000)});return new NextResponse(await response.text(),{status:response.status,headers:{"content-type":"application/json"}});}catch{return NextResponse.json({detail:"Upload service unavailable"},{status:502});}
}
