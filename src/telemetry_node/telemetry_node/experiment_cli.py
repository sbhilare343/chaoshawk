"""Reproducible offline chaos-metric command line tools."""
import argparse
import csv
import json
import os
from datetime import datetime, timezone

from .chaos_metrics import generate_lorenz, largest_lyapunov_rosenstein, analyze_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    lorenz = sub.add_parser('lorenz', help='Generate a Lorenz reference trajectory')
    lorenz.add_argument('--duration', type=float, default=40.0)
    lorenz.add_argument('--dt', type=float, default=0.01)
    lorenz.add_argument('--noise-std', type=float, default=0.0)
    lorenz.add_argument('--seed', type=int, default=0)
    lorenz.add_argument('--output-dir', default='results')
    estimate = sub.add_parser('estimate', help='Estimate the largest exponent from CSV')
    estimate.add_argument('csv')
    estimate.add_argument('--dt', type=float, help='Override inferred median timestamp interval')
    estimate.add_argument('--column', default='ax')
    estimate.add_argument('--output-dir', default='results')
    wind = sub.add_parser('wind', help='Convert Lorenz state into reproducible wind input CSV')
    wind.add_argument('--duration', type=float, default=40.0)
    wind.add_argument('--dt', type=float, default=0.01)
    wind.add_argument('--scale', type=float, default=0.2,
                      help='m/s per Lorenz state unit')
    wind.add_argument('--seed', type=int, default=0)
    wind.add_argument('--output-dir', default='results')
    evaluate = sub.add_parser('evaluate', help='Compute flight error metrics from odometry CSV')
    evaluate.add_argument('csv')
    evaluate.add_argument('--reference-x', type=float, default=0.0)
    evaluate.add_argument('--reference-y', type=float, default=0.0)
    evaluate.add_argument('--output-dir', default='results')
    demo = sub.add_parser('demo', help='Run matched baseline and supervised reference experiments')
    demo.add_argument('--duration', type=float, default=35.0)
    demo.add_argument('--seed', type=int, default=7)
    demo.add_argument('--output-dir', default='results/demo')
    report = sub.add_parser('report', help='Build figures and TeX report from two telemetry CSVs')
    report.add_argument('baseline_csv')
    report.add_argument('supervised_csv')
    report.add_argument('--output-dir', default='results/report')
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = os.path.join(args.output_dir, f'{args.command}_{run_id}')

    if args.command == 'demo':
        from .research_pipeline import ExperimentConfig, run_experiment, save_experiment
        for mode in ('baseline', 'supervised'):
            config = ExperimentConfig(duration_s=args.duration, seed=args.seed, mode=mode)
            save_experiment(run_experiment(config), args.output_dir, config)
        metadata = {'output_dir': os.path.abspath(args.output_dir), 'modes': ['baseline', 'supervised'],
                    'seed': args.seed, 'duration_s': args.duration}
    elif args.command == 'report':
        from .report import build_report
        tex_path, figure_path, pdf_path = build_report(args.baseline_csv, args.supervised_csv, args.output_dir)
        metadata = {'tex': tex_path, 'figure': figure_path, 'pdf': pdf_path,
                    'pdf_command': f'pdflatex -output-directory {args.output_dir} {tex_path}'}
    elif args.command in ('lorenz', 'wind'):
        time_values, states = generate_lorenz(
            duration=args.duration, dt=args.dt,
            noise_std=args.noise_std if args.command == 'lorenz' else 0.0,
            seed=args.seed
        )
        csv_path = out + '.csv'
        with open(csv_path, 'x', newline='') as stream:
            writer = csv.writer(stream)
            if args.command == 'wind':
                writer.writerow(('time_s', 'wind_north_m_s', 'wind_east_m_s', 'wind_up_m_s'))
                writer.writerows(
                    (t, *(args.scale * component for component in state))
                    for t, state in zip(time_values, states)
                )
            else:
                writer.writerow(('time_s', 'x', 'y', 'z'))
                writer.writerows(zip(time_values, *states.T))
        if args.command == 'wind':
            metadata = {
                'experiment_id': run_id, 'created_utc': run_id,
                'input': 'Lorenz ODE converted to wind',
                'duration_s': args.duration, 'dt_s': args.dt,
                'scale_m_s_per_state_unit': args.scale,
                'random_seed': args.seed, 'wind_csv': csv_path,
                'note': 'CSV is generated input data; no Gazebo force plugin consumes it yet',
            }
        else:
            value = largest_lyapunov_rosenstein(states, args.dt)
            metadata = {
                'experiment_id': run_id, 'created_utc': run_id,
                'input': 'Lorenz ODE', 'duration_s': args.duration,
                'discard_s': 5.0, 'dt_s': args.dt, 'noise_std': args.noise_std,
                'random_seed': args.seed,
                'estimator': 'Rosenstein delay embedding',
                'largest_exponent_per_s': value, 'raw_csv': csv_path,
                'interpretation': 'finite-window estimate; not a UAV chaos diagnosis',
            }
    elif args.command == 'estimate':
        value, timing = analyze_csv(args.csv, args.dt, column=args.column)
        metadata = {
            'experiment_id': run_id, 'created_utc': run_id,
            'input': os.path.abspath(args.csv), 'column': args.column,
            **timing, 'estimator': 'Rosenstein delay embedding',
            'largest_exponent_per_s': value,
            'interpretation': 'instability indicator; not proof of UAV chaos',
        }
    else:
        import numpy as np
        with open(args.csv, newline='') as stream:
            rows = list(csv.DictReader(stream))
        if not rows or not {'x', 'y', 'z'}.issubset(rows[0]):
            raise ValueError('Odometry CSV must include x, y, and z columns')
        xyz = np.asarray([[float(row[k]) for k in ('x', 'y', 'z')] for row in rows])
        reference = np.array([args.reference_x, args.reference_y])
        error = np.linalg.norm(xyz[:, :2] - reference, axis=1)
        metadata = {
            'experiment_id': run_id, 'created_utc': run_id,
            'source': os.path.abspath(args.csv), 'samples': len(rows),
            'reference_xy_m': reference.tolist(),
            'horizontal_rms_error_m': float(np.sqrt(np.mean(error ** 2))),
            'horizontal_max_error_m': float(np.max(error)),
            'altitude_mean_m': float(np.mean(xyz[:, 2])),
            'altitude_std_m': float(np.std(xyz[:, 2])),
        }
    with open(out + '.json', 'x') as stream:
        json.dump(metadata, stream, indent=2)
        stream.write('\n')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
