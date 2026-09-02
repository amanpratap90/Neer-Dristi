import React from "react";

export default function Section({
  number,
  title,
  description,
  children,
}) {
  return (
    <section className="report-section">

      <div className="section-header">

        <span className="section-number">
          {number}
        </span>

        <div>
          <span className="section-kicker">
            FLOOD INTELLIGENCE
          </span>

          <h2>{title}</h2>

          {description && (
            <p>{description}</p>
          )}
        </div>

      </div>

      <div className="section-content">
        {children}
      </div>

    </section>
  );
}