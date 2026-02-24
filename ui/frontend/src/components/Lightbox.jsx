export default function Lightbox({ src, label, onClose }) {
    return (
        <div className="lightbox-overlay" onClick={onClose}>
            <div className="lightbox-box" onClick={e => e.stopPropagation()}>
                <div className="lightbox-header">
                    <span className="lightbox-label">{label}</span>
                    <div className="lightbox-actions">
                        <a href={src} download className="lightbox-download">📥 Download</a>
                        <button className="lightbox-close" onClick={onClose}>✕</button>
                    </div>
                </div>
                <img src={src} alt={label} className="lightbox-img" />
            </div>
        </div>
    )
}
