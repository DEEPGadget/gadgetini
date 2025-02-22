import { NextResponse } from "next/server";

export async function POST(req) {
  try {
    const payload = await req.json();

    console.log("Received IP Configuration Payload:", payload);

    return NextResponse.json({
      success: true,
      message: "Payload received successfully",
      receivedData: payload,
    });
  } catch (error) {
    console.error("Error processing IP payload:", error);
    return NextResponse.json(
      { success: false, error: "Failed to process request" },
      { status: 500 }
    );
  }
}
