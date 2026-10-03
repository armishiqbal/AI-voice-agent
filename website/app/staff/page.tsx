import { metadata } from "@/lib/site";
export const generateMetadata = () => ({ ...metadata("Staff access", "Awaaz Estate staff workspace.", "/staff"), robots: { index: false, follow: false } });
export default function Staff() { return <section className="section container prose"><p className="eyebrow">Staff workspace</p><h1>Staff access is not available yet</h1><p>This workspace will open when staff authentication and permissions are configured. Company records and administrative tools are not available through this page.</p></section>; }
