// Text-based logo — works at any size, faithful to the IF brand mark concept
export default function IFLogo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizes = {
    sm: 'text-lg tracking-tight',
    md: 'text-2xl tracking-tight',
    lg: 'text-4xl tracking-tight',
  }
  return (
    <span className={`font-bold ${sizes[size]} select-none`} aria-label="IF">
      <span className="text-[#0C0C18]">I</span>
      <span className="text-[#1A5FFF]">F</span>
    </span>
  )
}
