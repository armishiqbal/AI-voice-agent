export async function sessionRequest(path:string,init:RequestInit={}){
 const headers=new Headers(init.headers);headers.set("content-type","application/json");
 if(!["GET","HEAD"].includes(init.method||"GET")){
  let csrf=sessionStorage.getItem("awaaz_csrf");if(!csrf){const r=await fetch("/api/session/auth/csrf");if(!r.ok)throw Error("Sign in first");const v=await r.json();csrf=String(v.csrf_token);sessionStorage.setItem("awaaz_csrf",csrf);}
  headers.set("x-csrf-token",csrf);
 }
 const r=await fetch(`/api/session/${path}`,{...init,headers,signal:AbortSignal.timeout(15000)});
 const v:unknown=await r.json();if(!r.ok){const detail=typeof v==="object"&&v!==null&&"detail"in v?String(v.detail):"Request failed";throw Error(detail);}return v;
}
