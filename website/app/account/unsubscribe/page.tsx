import {Unsubscribe} from "@/components/Unsubscribe";
export const metadata={title:"Unsubscribe",robots:{index:false,follow:false}};
export default async function Page({searchParams}:{searchParams:Promise<{token?:string}>}){return <Unsubscribe token={(await searchParams).token||""}/>;}
