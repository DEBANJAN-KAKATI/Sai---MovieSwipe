/** The sai wordmark (generated from branding/sai-logo-source.png by branding/make_assets.py). */
export function BrandLogo({ height = 30 }: { height?: number }) {
  return <img src="/sai-wordmark.png" alt="sai" className="brand-logo" style={{ height }} draggable={false} />;
}
