/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#0ea5a4",
        accent: "#ff6b6b",
        bg: "#0f172a",
        card: "#0b1220",
      },
    },
  },
  plugins: [],
};
