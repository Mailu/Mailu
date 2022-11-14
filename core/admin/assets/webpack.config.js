const path = require('path');
const webpack = require('webpack');
const css = require('mini-css-extract-plugin');
const mini = require('css-minimizer-webpack-plugin');
const terse = require('terser-webpack-plugin');
const compress = require('compression-webpack-plugin');

module.exports = {
    mode: 'production',
    entry: {
        app: {
            import: ['./assets/app.css', './assets/mailu.png', './assets/app.js'],
            dependOn: 'vendor',
        },
        vendor: './assets/vendor.js',
    },
    output: {
        path: path.resolve(__dirname, 'static/'),
        filename: '[name].js',
        assetModuleFilename: '[name][ext]',
    },
    module: {
        rules: [
            {
                test: /\.js$/,
                use: ['babel-loader', 'import-glob'],
            },
            {
                test: /\.s?css$/i,
                use: [css.loader, 'css-loader', 'sass-loader'],
            },
            {
                test: /\.less$/i,
                use: [css.loader, 'css-loader', 'less-loader'],
            },
            {
                test: /\.(json|png|svg|jpg|jpeg|gif)$/i,
                type: 'asset/resource',
            },
        ],
    },
    plugins: [
        new css({
            filename: '[name].css',
            chunkFilename: '[id].css',
        }),
        new webpack.ProvidePlugin({
            $: 'jquery',
            jQuery: 'jquery',
            ClipboardJS: 'clipboard',
        }),
        new compress({
            filename: '[path][base].gz',
            algorithm: "gzip",
            exclude: /\.(png|gif|jpe?g)$/,
            threshold: 5120,
            minRatio: 0.8,
            deleteOriginalAssets: false,
        }),
    ],
    optimization: {
        minimize: true,
        minimizer: [
            new terse(),
            new mini({
                minimizerOptions: {
                    preset: [
                        'default', {
                            discardComments: { removeAll: true },
                        },
                    ],
                },
            }),
        ],
    },
};
