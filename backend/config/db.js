import mongoose from "mongoose";

export async function connectDB() {
  try {
    await mongoose.connect(process.env.MONGO_URI);

    console.log("==============================================");
    console.log("CHETAKAI MONGODB");
    console.log("==============================================");
    console.log("MongoDB connected");
    console.log("Database:", mongoose.connection.name);
    console.log("==============================================");
  } catch (error) {
    console.error("MongoDB connection failed:");
    console.error(error.message);

    process.exit(1);
  }
}