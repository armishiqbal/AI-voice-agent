import {NextRequest} from "next/server";
import {proxy} from "@/lib/proxy";
export async function POST(r:NextRequest){return proxy(r,"public/alerts/unsubscribe");}
