export const statusTone = (s: string) => (s === "Published" ? "green" : s === "Archived" ? "slate" : "amber");
export const subTone = (s: string) => (s === "Active" ? "green" : s === "Trial" ? "brand" : s === "Expired" ? "red" : "slate");
