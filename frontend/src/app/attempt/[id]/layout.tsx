import { Open_Sans } from "next/font/google";

// The online CCL test is set in Open Sans; the player uses it too so it looks and reads the same.
const openSans = Open_Sans({ subsets: ["latin", "latin-ext"], weight: ["300", "400", "600", "700"] });

export default function AttemptLayout({ children }: { children: React.ReactNode }) {
  return <div className={openSans.className}>{children}</div>;
}
