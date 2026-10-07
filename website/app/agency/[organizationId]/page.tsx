import {AgencyWorkspace} from "@/components/AgencyWorkspace";
export const metadata={title:"Agency workspace",robots:{index:false,follow:false}};
export default async function Page({params}:{params:Promise<{organizationId:string}>}){return <AgencyWorkspace organizationId={(await params).organizationId}/>;}
