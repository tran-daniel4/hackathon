export default function Loading() {
  return (
    <div className="bg-[#0a0a0f] text-white min-h-screen flex flex-col items-center justify-center gap-6">
      <div className="text-[11px] uppercase tracking-[0.2em] opacity-40">
        Loading...
      </div>
      <div className="w-[1px] h-12 bg-white animate-pulse opacity-20" />
    </div>
  );
}
