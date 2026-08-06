import Link from 'next/link';

type PhoneERPLogoProps = {
  href?: string;
  compact?: boolean;
  className?: string;
};

export default function PhoneERPLogo({
  href = '/',
  compact = false,
  className = '',
}: PhoneERPLogoProps) {
  const logo = (
    <span className={`phoneerp-logo ${className}`.trim()}>
      <span className="phoneerp-logo-mark" aria-hidden="true">
        <span>P</span>
        <span>E</span>
      </span>
      {!compact && (
        <span className="phoneerp-logo-wordmark">
          Phone<span>ERP</span>
        </span>
      )}
    </span>
  );

  return href ? (
    <Link href={href} aria-label="PhoneERP home" className="inline-flex">
      {logo}
    </Link>
  ) : logo;
}
