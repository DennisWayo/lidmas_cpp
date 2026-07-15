import { useState } from "react";

interface HelpCard {
  title: string;
  description: string;
  cta: string;
  href: string;
}

interface FaqItem {
  question: string;
  answer: string;
}

const DOCUMENTATION_URL = "https://gottesman-software.github.io/lidmas_cpp/";

const helpCards: HelpCard[] = [
  {
    title: "Getting Started Guide",
    description: "Learn setup, initial configuration, and your first execution workflow.",
    cta: "Read Guide →",
    href: `${DOCUMENTATION_URL}getting-started/`,
  },
  {
    title: "API Documentation",
    description: "Reference for integrating LiDMaS+ with external systems and automations.",
    cta: "View API Docs →",
    href: `${DOCUMENTATION_URL}hardware-integration/`,
  },
  {
    title: "Configuration Reference",
    description: "Detailed definitions for every runtime parameter and environment option.",
    cta: "View Configs →",
    href: `${DOCUMENTATION_URL}cli-reference/`,
  },
  {
    title: "Troubleshooting Guide",
    description: "Common failure modes and recommended remediation paths.",
    cta: "Troubleshoot →",
    href: `${DOCUMENTATION_URL}reproducibility-citation/`,
  },
  {
    title: "Architecture Overview",
    description: "Explore services, data flow, and control-plane boundaries.",
    cta: "Learn Architecture →",
    href: `${DOCUMENTATION_URL}architecture/`,
  },
  {
    title: "Release Notes",
    description: "Track features, fixes, and compatibility changes per version.",
    cta: "View Releases →",
    href: "https://github.com/Gottesman-Software/lidmas_cpp/releases",
  },
];

const faqs: FaqItem[] = [
  {
    question: "How do I add a new provider to the decoder?",
    answer:
      "Go to Providers, click Add Provider, configure host, credentials, and region, then run Test Connection before saving.",
  },
  {
    question: "What does the success rate metric represent?",
    answer:
      "Success rate is computed as successful runs divided by total runs over the selected interval.",
  },
  {
    question: "How can I export logs for analysis?",
    answer:
      "Open Logs, apply filters, and click Download to export in CSV or JSON format.",
  },
  {
    question: "What is the maximum job timeout?",
    answer:
      "Default timeout is 3600 seconds. You can change it in Settings according to policy.",
  },
  {
    question: "How does provider failover work?",
    answer:
      "If a provider turns unhealthy, queued work is reassigned to available providers when failover is enabled.",
  },
];

export function HelpPage() {
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null);
  const [search, setSearch] = useState("");

  const visibleCards = helpCards.filter((card) =>
    `${card.title} ${card.description}`.toLowerCase().includes(search.toLowerCase()),
  );
  const visibleFaqs = faqs.filter((faq) =>
    `${faq.question} ${faq.answer}`.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <>
      <div className="header">
        <h1>Help &amp; Support</h1>
        <p>Get help with LiDMaS+ Decoder, access documentation, and contact support</p>
        <input
          type="text"
          className="search-box"
          placeholder="Search help docs..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>

      <div className="content-grid">
        {visibleCards.map((card) => (
          <article key={card.title} className="card">
            <div className="card-title">{card.title}</div>
            <div className="card-description">{card.description}</div>
            <a
              href={card.href}
              className="card-link"
              target="_blank"
              rel="noreferrer"
            >
              {card.cta}
            </a>
          </article>
        ))}
      </div>

      <div className="section-title">Frequently Asked Questions</div>
      {visibleFaqs.map((faq, index) => (
        <div
          key={faq.question}
          className={`faq-item ${expandedFaq === index ? "open" : ""}`}
          onClick={() => setExpandedFaq(expandedFaq === index ? null : index)}
        >
          <div className="faq-question">
            <span>{faq.question}</span>
            <span className="faq-icon">▼</span>
          </div>
          <div className="faq-answer">{faq.answer}</div>
        </div>
      ))}

      <div className="section-title">Contact &amp; Support</div>
      <div className="contact-section">
        <div className="contact-item">
          <div className="contact-title">Email Support</div>
          <a href="mailto:dwayo3@gatech.edu" className="contact-value">
            dwayo3@gatech.edu
          </a>
          <div className="contact-hint">Response time: 2-4 hours</div>
        </div>
        <div className="contact-item">
          <div className="contact-title">Documentation</div>
          <a href={DOCUMENTATION_URL} className="contact-value" target="_blank" rel="noreferrer">
            Lidmas+ Documentation
          </a>
          <div className="contact-hint">Full online reference</div>
        </div>
        <div className="contact-item">
          <div className="contact-title">Community Forum</div>
          <a href={DOCUMENTATION_URL} className="contact-value" target="_blank" rel="noreferrer">
            Lidmas+ Documentation
          </a>
          <div className="contact-hint">Ask questions, share tips</div>
        </div>
      </div>
    </>
  );
}
