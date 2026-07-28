import React from 'react';
import { Header } from '../components/Header';
import { Hero } from '../components/Hero';
import { Features } from '../components/Features';
import { ProductDemo } from '../components/ProductDemo';
import { WhyMock } from '../components/WhyMock';
import { Testimonials } from '../components/Testimonials';
import { Pricing } from '../components/Pricing';
import { FAQ } from '../components/FAQ';
import { CTA } from '../components/CTA';
import { Footer } from '../components/Footer';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0A0B0D] overflow-x-hidden">
      <Header />
      <main>
        <Hero />
        <Features />
        <ProductDemo />
        <WhyMock />
        <Testimonials />
        <Pricing />
        <FAQ />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}











