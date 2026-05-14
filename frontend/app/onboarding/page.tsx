"use client";

import { useState } from "react";
import StepOne from "./components/StepOne";
import StepTwo from "./components/StepTwo";
import StepThree from "./components/StepThree";
import { ContractorResponse } from "@/lib/onboarding-api";

const STEPS = [
  { label: "Business Profile" },
  { label: "Rate Card" },
  { label: "Go Live" },
];

export default function OnboardingPage() {
  const [step, setStep] = useState(1);
  const [contractor, setContractor] = useState<ContractorResponse | null>(null);
  const [workType, setWorkType] = useState<string>("painting");

  return (
    <div className="min-h-screen bg-gray-50 flex items-start justify-center pt-12 px-4">
      <div className="w-full max-w-lg">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-gray-900">Set up QuoteWise</h1>
          <p className="mt-1 text-sm text-gray-500">
            Get your AI-powered quoting assistant live in minutes
          </p>
        </div>

        {/* Step progress */}
        <div className="flex items-center justify-center mb-8">
          {STEPS.map((s, i) => {
            const num = i + 1;
            const done = step > num;
            const active = step === num;
            return (
              <div key={num} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                      done
                        ? "bg-green-500 text-white"
                        : active
                        ? "bg-blue-600 text-white"
                        : "bg-gray-200 text-gray-500"
                    }`}
                  >
                    {done ? "✓" : num}
                  </div>
                  <span
                    className={`mt-1 text-xs font-medium ${
                      active ? "text-blue-600" : done ? "text-green-600" : "text-gray-400"
                    }`}
                  >
                    {s.label}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <div
                    className={`w-16 h-0.5 mx-2 mb-5 transition-colors ${
                      done ? "bg-green-400" : "bg-gray-200"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* Step card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 px-6 py-8">
          {step === 1 && (
            <StepOne
              onComplete={(c) => {
                setContractor(c);
                setStep(2);
              }}
            />
          )}
          {step === 2 && contractor && (
            <StepTwo
              contractorId={contractor.id}
              apiKey={contractor.api_key}
              onComplete={(wt) => {
                setWorkType(wt);
                setStep(3);
              }}
            />
          )}
          {step === 3 && contractor && (
            <StepThree contractor={contractor} workType={workType} />
          )}
        </div>
      </div>
    </div>
  );
}
