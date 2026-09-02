import Link from "next/link";
import ThemeToggle from "./ThemeToggle";
import styles from "./Header.module.css";

export default function Header() {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand} aria-label="ACAE — home">
          <svg
            className={styles.mark}
            viewBox="0 0 32 32"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M9.5 7.5H7.5a2 2 0 0 0-2 2v2"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <path
              d="M22.5 7.5h2a2 2 0 0 1 2 2v2"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <path
              d="M9.5 24.5H7.5a2 2 0 0 1-2-2v-2"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <path
              d="M22.5 24.5h2a2 2 0 0 0 2-2v-2"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <circle cx="19" cy="14" r="2.75" fill="var(--color-incorrect)" />
          </svg>
          <span className={styles.wordmark}>ACAE</span>
        </Link>

        <p className={styles.fullName}>Adaptive Cognitive Assessment Engine</p>

        <nav className={styles.nav} aria-label="Primary">
          <Link href="/" className={styles.navLink}>
            Quiz
          </Link>
          <Link href="/results" className={styles.navLink}>
            Results
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}