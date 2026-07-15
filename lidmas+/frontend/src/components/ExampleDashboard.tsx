/**
 * EXAMPLE: Modern component using Shadcn/ui + Tailwind
 * Shows best practices for the research UI setup
 */

import { useState } from "react"
import { useForm } from "react-hook-form"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Settings, AlertCircle, CheckCircle2 } from "lucide-react"

interface FormData {
  name: string
  email: string
}

export function ExampleDashboard() {
  const [items] = useState([
    { id: 1, name: "Provider A", status: "active", count: 42 },
    { id: 2, name: "Provider B", status: "warning", count: 8 },
    { id: 3, name: "Provider C", status: "error", count: 0 },
  ])

  const { register, handleSubmit } = useForm<FormData>()

  const onSubmit = (data: FormData) => {
    console.log("Form data:", data)
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case "active":
        return "success"
      case "warning":
        return "warning"
      case "error":
        return "destructive"
      default:
        return "default"
    }
  }

  const getStatusIcon = (status: string) => {
    if (status === "active") return <CheckCircle2 className="w-4 h-4" />
    if (status === "error") return <AlertCircle className="w-4 h-4" />
    return null
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header Section */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Dashboard Example</h1>
          <p className="text-muted-foreground mt-1">
            Shows best practices using Shadcn/ui + Tailwind
          </p>
        </div>
        <Button variant="outline" size="icon">
          <Settings className="w-4 h-4" />
        </Button>
      </div>

      {/* Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: "Active Providers", value: "12", variant: "success" as const },
          { label: "Jobs Queued", value: "148", variant: "warning" as const },
          { label: "Storage Used", value: "2.4 GB", variant: "default" as const },
        ].map((metric) => (
          <Card key={metric.label}>
            <CardHeader className="pb-2">
              <CardDescription className="text-sm">{metric.label}</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{metric.value}</p>
              <Badge variant={metric.variant} className="mt-2">
                {metric.variant}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Form Card */}
      <Card>
        <CardHeader>
          <CardTitle>Configuration Form</CardTitle>
          <CardDescription>
            Example using React Hook Form + Tailwind styling
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Name
                </label>
                <Input
                  {...register("name", { required: true })}
                  placeholder="Enter name"
                  className="h-9"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Email
                </label>
                <Input
                  {...register("email", { required: true })}
                  placeholder="Enter email"
                  type="email"
                  className="h-9"
                />
              </div>
            </div>
            <Button type="submit" className="w-full md:w-auto">
              Submit
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Table Card */}
      <Card>
        <CardHeader>
          <CardTitle>Providers Table</CardTitle>
          <CardDescription>
            Example data table using Shadcn/ui Table component
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Job Count</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(item.status)}
                        <Badge variant={getStatusVariant(item.status)}>
                          {item.status}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {item.count}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Tailwind Utility Classes Examples */}
      <Card className="bg-muted/50">
        <CardHeader>
          <CardTitle className="text-base">Tailwind Utilities Cheat Sheet</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div>
            <span className="font-mono text-primary">Spacing:</span>
            <p className="text-muted-foreground">
              p-4 (padding), m-2 (margin), gap-6 (flex gap)
            </p>
          </div>
          <div>
            <span className="font-mono text-primary">Colors:</span>
            <p className="text-muted-foreground">
              text-primary, bg-secondary, border-border
            </p>
          </div>
          <div>
            <span className="font-mono text-primary">Responsive:</span>
            <p className="text-muted-foreground">
              md:grid-cols-3 (medium screens), lg:text-lg (large screens)
            </p>
          </div>
          <div>
            <span className="font-mono text-primary">Effects:</span>
            <p className="text-muted-foreground">
              shadow-lg, rounded-lg, hover:bg-accent, transition-colors
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
