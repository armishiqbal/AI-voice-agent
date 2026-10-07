import DevelopmentStaffPanel from "@/components/DevelopmentStaffPanel";
import {ModerationWorkspace} from "@/components/ModerationWorkspace";
export const metadata={title:"Staff workspace",robots:{index:false,follow:false}};
export default function Page(){return process.env.NODE_ENV==="development"&&process.env.AWAAZ_DEV_STAFF_TOOLS==="true"?<DevelopmentStaffPanel/>:<ModerationWorkspace/>;}
