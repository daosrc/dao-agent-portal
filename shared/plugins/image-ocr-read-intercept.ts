import { type Plugin, tool } from "@opencode-ai/plugin";
import path from "path";
import { readFileSync, existsSync } from "fs";
import { execSync } from "child_process";

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"]);
const MAX_DEFAULT_LINES = 2000;

function isImageFile(fp: string): boolean {
  const lower = fp.toLowerCase();
  for (const ext of IMAGE_EXTS) {
    if (lower.endsWith(ext)) return true;
  }
  return false;
}

const SCRIPT = "~/.claude/skills/image-ocr/scripts/analyze_image.py";

export const ImageOcrReadIntercept: Plugin = async () => {
  return {
    tool: {
      Read: tool({
        description:
          "Read a file from the local filesystem. " +
          "For image files, uses external vision API (this model cannot read images natively).",
        args: {
          filePath: tool.schema.string().describe("The absolute path to the file to read"),
          offset: tool.schema.number().optional().describe("Line number to start reading from (1-indexed)"),
          limit: tool.schema.number().optional().describe("Maximum number of lines to read"),
        },
        async execute(args, { directory }) {
          let fp = args.filePath;
          if (!path.isAbsolute(fp)) {
            fp = path.join(directory ?? process.cwd(), fp);
          }

          if (!existsSync(fp)) {
            return `File not found: ${fp}`;
          }

          if (isImageFile(fp)) {
            try {
              const home = process.env.HOME || "";
              const output = execSync(
                `python3 ${SCRIPT.replace("~", home)} "${fp}" "Describe this image in detail"`,
                { encoding: "utf-8", timeout: 60000 },
              );
              return output.trim();
            } catch (e: any) {
              return `[Image analysis failed: ${e.message}]`;
            }
          }

          const content = readFileSync(fp, "utf-8");
          const lines = content.split("\n");
          const totalLines = lines.length;
          const start = args.offset ?? 1;
          const rawLimit = args.limit ?? MAX_DEFAULT_LINES;
          const end = Math.min(start + rawLimit - 1, totalLines);
          const excerpt = lines.slice(start - 1, end);
          const numbered = excerpt.map((line, i) => `${start + i}: ${line}`).join("\n");
          let result = `${fp}\n${numbered}`;
          if (end < totalLines) {
            result += `\n... (${totalLines - end} lines omitted)`;
          }
          return result;
        },
      }),
    },
  };
};
